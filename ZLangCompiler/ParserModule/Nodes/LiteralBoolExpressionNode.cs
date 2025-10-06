using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralBoolExpressionNode : AstNode
{
    public Token Token { get; }
    public bool Value { get; }

    public LiteralBoolExpressionNode(Token token)
    {
        Token = token;
        Value = bool.Parse(token.Lexeme);
    }
    
    public override void Accept(IAstNodeVisitor visitor)
    {
        visitor.VisitLiteralBoolExpression(this);
    }
}