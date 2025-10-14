using LexerModule;

namespace ParserModule.Nodes;

public sealed class LiteralBoolExpressionNode : ExpressionNode
{
    public Token Token { get; }
    public bool Value { get; }

    public LiteralBoolExpressionNode(Token token)
    {
        Token = token;
        Value = bool.Parse(token.Lexeme);
    }
    
    public override void Accept(IExpressionNodeVisitor visitor)
    {
        visitor.VisitLiteralBool(this);
    }
}