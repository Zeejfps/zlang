using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralIntegerExpressionNode : AstNode
{
    public Token Token { get; }
    public int Value { get; }

    public LiteralIntegerExpressionNode(Token token)
    {
        Token = token;
        Value = int.Parse(token.Lexeme);
    }

    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitIntegerNumberExpression(this);
    }
}